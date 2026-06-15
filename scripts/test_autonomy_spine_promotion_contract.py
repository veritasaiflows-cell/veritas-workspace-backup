#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import autonomy_spine_promotion_contract as contract


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def route(workflow_id: str, tier: str) -> dict:
    return {
        "workflow_id": workflow_id,
        "tier": tier,
        "effective_status": "route_only",
        "current_state": "test",
        "authority_boundary": "review-only",
    }


def test_contract_accepts_attention_promotion_without_authority_expansion() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "routes.json"
        write_json(path, {"routes": [route("WF55", "P1"), route("WF76", "P1"), route("WF74", "P1"), route("WF71", "P1")]})
        payload = contract.build_payload(path)
        assert payload["status"] == "ok"
        assert payload["validation"]["status"] == "ok"
        assert len(payload["promotion_rows"]) == 4
        assert payload["authority_boundary"]["paper_or_live_execution_allowed"] is False
        assert payload["authority_boundary"]["predictive_claim_allowed"] is False


def test_contract_warns_when_route_not_yet_wired() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "routes.json"
        write_json(path, {"routes": [route("WF55", "P2")]})
        payload = contract.build_payload(path)
        assert payload["status"] == "ok"
        assert payload["validation"]["status"] == "warning"
        assert payload["live_route_mismatches"][0]["workflow_id"] == "WF55"


if __name__ == "__main__":
    test_contract_accepts_attention_promotion_without_authority_expansion()
    test_contract_warns_when_route_not_yet_wired()
    print("autonomy_spine_promotion_contract_tests_passed")
