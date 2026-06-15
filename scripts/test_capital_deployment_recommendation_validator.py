from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import capital_deployment_recommendation_report as report
import capital_deployment_recommendation_validator as validator
import portfolio_mutation_proposal_generator as generator


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def sample_rec() -> dict[str, Any]:
    return {
        "ticker": "ETN",
        "current_state": "DEPLOYABLE NOW",
        "entry_band_status": "IN_BAND",
        "recommended_action": "deploy_candidate",
        "recommendation_action": "deploy",
        "macro_regime_check": "supportive",
        "thesis": "Electrification setup remains intact.",
        "base_case": "Base case remains review-worthy.",
        "bear_case": "Bear case blocks if invalidation fails.",
        "sizing_risk_envelope": {
            "review_boundary": "Owner-gated risk envelope only; no portfolio mutation or account-action authority.",
            "risk_thresholds": {"max_single_position_normal_pct": 15, "max_sector_pct": 25},
        },
        "sector_context": {"status": "available_review_only"},
        "official_earnings_bridge": {
            "status": "manual_required",
            "official_evidence_status": "manual_required",
            "official_evidence_posture": "review_only",
            "source_authority_level": "official_company_ir_metadata_only",
            "source_freshness": {"freshness_status": "unknown", "retrieval_status": "manual_required"},
            "evidence_claims": [],
            "unresolved_official_fields": sorted(validator.REQUIRED_UNRESOLVED_OFFICIAL_FIELDS),
            "manual_review_required": True,
            "summary": "Official earnings bridge remains manual-required/review-only.",
        },
        "blocked_reasons": [],
    }


def sample_bundle() -> dict[str, Any]:
    packet = generator.proposal_for(
        sample_rec(),
        window="post-close",
        generated_at="2026-05-14T00:00:00Z",
        daily={"source_freshness": {"overall_classification": "current", "trust_level": "clean"}},
        config={"portfolio": {"cash": 10}},
        config_meta={"workflow_state": "DEPLOYED", "coverage_lane": "execution", "entry_policy": "band_defined"},
        band_proposal={"band_status": "IN_BAND", "distance_to_band_pct": 0.0, "days_to_earnings": 85, "earnings_state": "CLEAR"},
        deployment_record={"action_state": "DEPLOYABLE NOW", "close": 419.0, "in_entry_band": True, "below_stop": False},
    )
    return {
        "schema_version": generator.SCHEMA_VERSION,
        "generated_at_utc": "2026-05-14T00:00:00Z",
        "status": "ok",
        "window": "post-close",
        "authority": dict(generator.TOP_LEVEL_AUTHORITY),
        "proposal_count": 1,
        "proposals": [packet],
        "stop_lines": ["Generated proposal packets are review surfaces and do not apply changes by themselves."],
    }


def test_validator_and_renderer(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "bundle.json"
        path.write_text(json.dumps(sample_bundle(), indent=2), encoding="utf-8")
        result = validator.build_report(path)
        expect(result["status"] == "ok", f"valid bundle should pass: {result}", errors)
        markdown = report.render_md(sample_bundle(), path)
        expect("Current Capital-Deployment Recommendation Packets" in markdown, "report title missing", errors)
        expect("portfolio note/model mutation workflow" in markdown, "approved scope should be visible", errors)
        expect("Trade/account action allowed: `false`" in markdown, "blocked trade/account boundary should be visible", errors)


def test_validator_blocks_bad_authority(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        bundle = sample_bundle()
        bundle["authority"]["trade_or_account_action_allowed"] = True
        bundle["proposals"][0]["why_now"] = "approval granted; execute trade"
        path = Path(td) / "bad.json"
        path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        result = validator.build_report(path)
        expect(result["status"] == "blocked", f"bad authority should block: {result}", errors)
        expect(result["summary"]["critical"] >= 2, f"should produce multiple critical findings: {result}", errors)


def test_validator_blocks_false_live_stop_label(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        bundle = sample_bundle()
        bundle["proposals"][0]["technical_gate"]["entry_band_status"] = "BELOW_STOP"
        bundle["proposals"][0]["technical_gate"]["band_status"] = "BELOW_STOP"
        bundle["proposals"][0]["technical_gate"]["below_stop"] = False
        path = Path(td) / "bad-stop-label.json"
        path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        result = validator.build_report(path)
        expect(result["status"] == "blocked", f"false live-stop label should block: {result}", errors)
        expect(any("BELOW_STOP is reserved" in str(item.get("issue")) for item in result["findings"]), f"semantic guard finding missing: {result}", errors)


def main() -> int:
    errors: list[str] = []
    test_validator_and_renderer(errors)
    test_validator_blocks_bad_authority(errors)
    test_validator_blocks_false_live_stop_label(errors)
    if errors:
        print("capital_deployment_recommendation_validator_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("capital_deployment_recommendation_validator_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
