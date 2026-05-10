from __future__ import annotations

from datetime import datetime, timezone

from source_freshness_classifier import classify_source_state, summarize_source_freshness

NOW = datetime(2026, 5, 10, 2, 0, tzinfo=timezone.utc)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def classify(**kwargs):
    base = {
        "source_key": "fixture",
        "path": "tmp/fixture.json",
        "required": True,
        "criticality": "critical",
        "generated_at_utc": "2026-05-10T01:30:00Z",
        "stale_after_hours": 8,
        "now": NOW,
    }
    base.update(kwargs)
    return classify_source_state(**base)


def main() -> int:
    errors: list[str] = []

    fresh = classify(status_raw="ok")
    expect(fresh["classification"] == "fresh", "ok current artifact should classify fresh", errors)
    expect(fresh["usable_for_canonical_mutation"] is False, "freshness never grants canonical mutation", errors)

    current = classify(status_raw="running")
    expect(current["classification"] == "current", "timely non-ok snapshot should classify current", errors)
    expect(current["usable_for_review"] is True, "current snapshot should remain usable for review", errors)

    manual = classify(status_raw="manual", manual_dependencies=["Fed target range"])
    expect(manual["classification"] == "manual_dependency", "manual raw status should classify manual_dependency", errors)
    expect(manual["usable_for_presentation"] is False, "manual dependency should block presentation-ready trust", errors)

    partial = classify(status_raw="partial", missing_fields=["Next FOMC distribution"])
    expect(partial["classification"] == "partial", "partial/missing fields should classify partial", errors)

    stale = classify(generated_at_utc="2026-05-09T00:00:00Z", status_raw="ok")
    expect(stale["classification"] == "stale", "old artifact should classify stale", errors)
    expect(stale["stop_line"] is False, "critical stale should degrade without automatic hard stop in this helper", errors)

    contradictory = classify(contradiction_refs=[{"left": "running", "right": "ok"}])
    expect(contradictory["classification"] == "contradictory", "contradictions should classify contradictory", errors)
    expect(contradictory["stop_line"] is True, "critical contradiction should stop line", errors)

    missing = classify(exists=False)
    expect(missing["classification"] == "missing", "missing source should classify missing", errors)
    expect(missing["stop_line"] is True, "critical missing source should stop line", errors)

    optional_missing = classify(exists=False, required=False, criticality="context")
    expect(optional_missing["classification"] == "missing", "optional missing remains visible as missing", errors)
    expect(optional_missing["stop_line"] is False, "optional missing should not stop line", errors)

    summary = summarize_source_freshness([fresh, manual, missing])
    expect(summary["overall_classification"] == "missing", "summary should preserve worst classification", errors)
    expect(summary["trust_level"] == "blocked", "critical missing should block summary trust", errors)
    expect(summary["canonical_note_mutation_allowed"] is False, "summary must fail-close canonical mutation", errors)
    expect(summary["capital_action_allowed"] is False, "summary must fail-close capital action", errors)

    if errors:
        print("source_freshness_classifier_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("source_freshness_classifier_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
