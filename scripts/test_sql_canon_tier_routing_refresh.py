from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sql_canon_tier_routing_refresh.py"

spec = importlib.util.spec_from_file_location("sql_canon_tier_routing_refresh", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def router_payload(expected_count: int = 300) -> dict:
    return {
        "status": "ok",
        "summary": {"active_ticker_count": expected_count},
        "validation": {"status": "ok", "checks": []},
    }


def router_rows(count: int = 300) -> list[dict]:
    return [
        {
            "ticker": f"T{i:03d}",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        }
        for i in range(count)
    ]


def test_validate_source_accepts_current_dynamic_300_row_router_packet() -> None:
    assert module.validate_source(router_payload(), router_rows()) == []


def test_validate_source_blocks_partial_source_even_when_not_200_specific() -> None:
    errors = module.validate_source(router_payload(expected_count=300), router_rows(count=299))
    assert "source_row_count_mismatch" in errors
    assert "source_row_count_not_200" not in errors


def test_validate_source_blocks_authority_widening() -> None:
    rows = router_rows()
    rows[0]["trade_or_execution_approved"] = True
    errors = module.validate_source(router_payload(), rows)
    assert "source_has_capital_or_execution_flags" in errors


def test_expected_row_count_can_fall_back_to_router_validation_check() -> None:
    payload = {
        "status": "ok",
        "validation": {
            "status": "ok",
            "checks": [
                {
                    "name": "active_universe_rows_present",
                    "ok": True,
                    "detail": 300,
                }
            ],
        },
    }
    assert module.expected_source_row_count(payload) == 300


if __name__ == "__main__":
    test_validate_source_accepts_current_dynamic_300_row_router_packet()
    test_validate_source_blocks_partial_source_even_when_not_200_specific()
    test_validate_source_blocks_authority_widening()
    test_expected_row_count_can_fall_back_to_router_validation_check()
    print("sql_canon_tier_routing_refresh tests passed")
