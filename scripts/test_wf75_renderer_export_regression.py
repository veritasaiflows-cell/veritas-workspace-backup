from datetime import datetime, timezone

from wf75_renderer_export_regression import build_router_renderer_pilot


def fake_route(question: str) -> dict:
    return {
        "question": question,
        "question_class": "ticker_intelligence",
        "answer_contract_v2": {
            "freshness_and_conflict_checks": {
                "final_answer_allowed": False,
                "missing_or_residue": ["source_open_required"],
            }
        },
        "source_open_requirements": [r"C:\private\proof.json"],
    }


def test_router_renderer_export_guard_is_internal_only() -> None:
    payload = build_router_renderer_pilot(
        route_builder=fake_route,
        now=datetime(2026, 8, 11, 4, 0, tzinfo=timezone.utc),
    )
    assert payload["pilot_count"] == 5
    assert payload["clean_internal_case_count"] == 5
    assert payload["all_seeded_bad_blocked"] is True
    assert payload["customer_or_external_delivery_allowed"] is False
    assert all(row["audience"] == "internal_anonymous_service_state" for row in payload["rows"])
    assert all(row["external_export_blocked"] is True for row in payload["rows"])
    assert all(row["recommendation_allowed"] is False for row in payload["rows"])
