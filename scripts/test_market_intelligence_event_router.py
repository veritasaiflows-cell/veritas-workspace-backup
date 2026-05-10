from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import market_intelligence_event_router as router

WORKSPACE = SCRIPTS_DIR.parent


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_router_boundaries(errors: list[str]) -> None:
    packet = router.build_packet("post-close")
    expect(packet.get("consumer_posture") == "review_only", "router output must be review_only", errors)
    expect(packet.get("canonical_mutation_allowed") is False, "router must not allow canonical mutation", errors)
    expect(packet.get("deployment_state_mutation_allowed") is False, "router must not allow deployment-state mutation", errors)
    expect(packet.get("trade_execution_allowed") is False, "router must not allow trade execution", errors)
    expect(packet.get("owner_review_required") is True, "router must keep owner review required", errors)
    source_freshness = packet.get("source_freshness") or {}
    expect(source_freshness.get("canonical_note_mutation_allowed") is False, "source freshness must not grant canonical mutation", errors)
    expect(source_freshness.get("capital_action_allowed") is False, "source freshness must not grant capital action", errors)
    expect(source_freshness.get("trust_level") in {"clean", "review_required", "blocked"}, "router must emit normalized source trust", errors)
    expect((packet.get("summary") or {}).get("event_count", 0) > 0, "live artifacts should produce at least one routed event", errors)
    for event in packet.get("events") or []:
        expect(event.get("owner_review_required") is True, "every event must require owner review", errors)
        expect(event.get("canonical_mutation_allowed") is False, "event must not allow canonical mutation", errors)
        expect(event.get("trade_execution_allowed") is False, "event must not allow trade execution", errors)
        expect(event.get("recommended_route") in {"no_route", "weekly_review", "thesis_review", "promotion_review", "risk_review", "deployment_review"}, "event route must use approved vocabulary", errors)
        expect(event.get("source_trust") in {"clean", "review_required", "blocked"}, "event must emit normalized source trust", errors)
        source_freshness = event.get("source_freshness") or {}
        expect(source_freshness.get("classification") in {"fresh", "current", "manual_dependency", "partial", "stale", "contradictory", "missing", "unknown"}, "event must emit source freshness classification", errors)
        expect(source_freshness.get("trust_level") in {"clean", "review_required", "blocked"}, "event source freshness must emit normalized trust", errors)
    expect(any(event.get("event_type") == "unresolved_truth" for event in packet.get("events") or []), "partial/stale source truth should emit an unresolved_truth event", errors)


def test_live_artifact_boundaries(errors: list[str]) -> None:
    path = WORKSPACE / "tmp" / "market-intelligence-events-post-close.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    expect(data.get("consumer_posture") == "review_only", "live router artifact must be review_only", errors)
    expect(data.get("canonical_mutation_allowed") is False, "live router artifact must not allow canonical mutation", errors)
    expect(data.get("trade_execution_allowed") is False, "live router artifact must not allow trade execution", errors)
    source_freshness = data.get("source_freshness") or {}
    expect(source_freshness.get("canonical_note_mutation_allowed") is False, "live source freshness must not allow canonical mutation", errors)
    expect(source_freshness.get("capital_action_allowed") is False, "live source freshness must not allow capital action", errors)


def test_no_route_event_contract(errors: list[str]) -> None:
    event = router.no_route_event("post-close")
    expect(event.get("recommended_route") == "no_route", "no-route event must use no_route vocabulary", errors)
    expect(event.get("materiality_score") == 0, "no-route event must be non-material", errors)
    expect(event.get("owner_review_required") is True, "no-route event remains owner-review visible", errors)
    expect(event.get("canonical_mutation_allowed") is False, "no-route event must not allow canonical mutation", errors)


def main() -> int:
    errors: list[str] = []
    test_router_boundaries(errors)
    test_live_artifact_boundaries(errors)
    test_no_route_event_contract(errors)
    if errors:
        print("market_intelligence_event_router_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("market_intelligence_event_router_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
