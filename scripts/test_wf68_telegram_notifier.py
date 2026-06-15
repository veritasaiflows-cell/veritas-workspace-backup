#!/usr/bin/env python3
"""Targeted tests for WF68 Telegram notifier."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import wf68_telegram_notifier as notifier


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def fresh_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def runtime(status: str = "ok") -> dict:
    return {
        "status": status,
        "handoff_status": "EXECUTION_PACKET_READY",
        "generated_at_utc": fresh_stamp(),
        "authority_clean": True,
        "validation_bad": [],
        "failure_reason": None,
    }


def router() -> dict:
    return {
        "status": "EXECUTION_PACKET_READY",
        "generated_at_utc": fresh_stamp(),
        "authority_clean": True,
        "authority": {
            "paper_or_live_order_submission_allowed": False,
            "live_trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "immediate_execution_recommendations": [
            {
                "ticker": "ETN",
                "packet_md": "tmp/intraday-alerts/execution-recommendations/execution-recommendation.etn.md",
                "recommended_order_terms": {
                    "symbol": "ETN",
                    "side": "buy",
                    "qty": 1.0,
                    "limit_price": 397.38,
                    "estimated_notional_usd": 397.38,
                    "time_in_force": "day",
                    "stop_reference": 362.67,
                },
            }
        ],
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        runtime_path = td / "runtime.json"
        router_path = td / "router.json"
        state_path = td / "state.json"
        output_json = td / "status.json"
        output_md = td / "status.md"

        write(runtime_path, runtime())
        write(router_path, router())
        rc = notifier.main([
            "--runtime", str(runtime_path),
            "--router", str(router_path),
            "--state", str(state_path),
            "--output-json", str(output_json),
            "--output-md", str(output_md),
        ])
        assert rc == 0
        result = json.loads(output_json.read_text(encoding="utf-8"))
        assert result["status"] == "DRY_RUN_READY", result
        assert "PREPARE" in result["message_preview"], result["message_preview"]
        assert "APPROVE is not active" in result["message_preview"], result["message_preview"]
        assert result["authority"]["paper_or_live_order_submission_allowed"] is False

        old = router()
        old["generated_at_utc"] = "2026-06-01T19:35:26Z"
        write(router_path, old)
        rc = notifier.main([
            "--runtime", str(runtime_path),
            "--router", str(router_path),
            "--state", str(state_path),
            "--output-json", str(output_json),
            "--output-md", str(output_md),
            "--max-age-minutes", "1",
        ])
        assert rc == 0
        stale = json.loads(output_json.read_text(encoding="utf-8"))
        assert stale["status"] == "BLOCKED", stale
        assert any(str(item).startswith("artifact_stale") for item in stale["blockers"]), stale

        malformed = router()
        malformed["immediate_execution_recommendations"][0]["recommended_order_terms"].pop("qty")
        malformed["immediate_execution_recommendations"][0]["recommended_order_terms"].pop("limit_price")
        write(router_path, malformed)
        rc = notifier.main([
            "--runtime", str(runtime_path),
            "--router", str(router_path),
            "--state", str(state_path),
            "--output-json", str(output_json),
            "--output-md", str(output_md),
        ])
        assert rc == 0
        malformed_result = json.loads(output_json.read_text(encoding="utf-8"))
        assert malformed_result["status"] == "DRY_RUN_READY", malformed_result
        assert "missing_qty" in malformed_result["message_preview"], malformed_result["message_preview"]
        assert "missing_limit" in malformed_result["message_preview"], malformed_result["message_preview"]

        quiet = router()
        quiet["status"] = "NO_REPLY"
        quiet["immediate_execution_recommendations"] = []
        write(router_path, quiet)
        rc = notifier.main([
            "--runtime", str(runtime_path),
            "--router", str(router_path),
            "--state", str(state_path),
            "--output-json", str(output_json),
            "--output-md", str(output_md),
        ])
        assert rc == 0
        quiet_result = json.loads(output_json.read_text(encoding="utf-8"))
        assert quiet_result["status"] == "NO_REPLY", quiet_result

        rc = notifier.main([
            "--runtime", str(td / "missing-runtime.json"),
            "--router", str(td / "missing-router.json"),
            "--state", str(state_path),
            "--output-json", str(output_json),
            "--output-md", str(output_md),
            "--delivery-test",
        ])
        assert rc == 0
        delivery_test = json.loads(output_json.read_text(encoding="utf-8"))
        assert delivery_test["status"] == "DRY_RUN_READY", delivery_test
        assert delivery_test["message_kind"] == "delivery_test", delivery_test
        assert "DELIVERY TEST ONLY" in delivery_test["message_preview"], delivery_test["message_preview"]
        assert "No market signal" in delivery_test["message_preview"], delivery_test["message_preview"]
        assert delivery_test["authority"]["paper_or_live_order_submission_allowed"] is False

    print("wf68_telegram_notifier targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
