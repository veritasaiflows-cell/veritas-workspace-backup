#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "startup_brief_packet.py"


def load_module():
    spec = importlib.util.spec_from_file_location("startup_brief_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_build_payload_from_existing_packets() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        module.ROOT = root
        module.TMP = tmp
        module.FUTURE_PACKET = tmp / "future-session-enhancement-packet.json"
        module.PM_PACKET = tmp / "pm-control-packet.json"
        module.CRON_PACKET = tmp / "cron-control-packet.json"

        write_json(module.FUTURE_PACKET, {
            "workflow_capsules": [
                {"workflow_id": "WF85", "effective_status": "ready"},
                {"workflow_id": "WF84", "effective_status": "ready"},
            ]
        })
        write_json(module.PM_PACKET, {
            "status": "ok",
            "summary": {
                "implementation_queue": {"ready_job_count": 10, "blocked_job_count": 0},
                "pm_readiness": {"readiness_band": "yellow"},
                "finance_domain_repair_digest": {
                    "implementation_blocker_count": 0,
                    "control_plane_blocker_count": 0,
                    "finance_domain_repair_item_count": 200,
                    "tier_a_b_missing_decision_grade_band_count": 15,
                    "tier_a_b_missing_decision_grade_band_tickers": ["ACN"],
                },
            },
        })
        write_json(module.CRON_PACKET, {
            "status": "ok",
            "summary": {"escalation_signal_count": 0, "blocked_count": 0},
        })

        payload = module.build_payload(max_age_minutes=90)
        assert payload["status"] == "ok"
        assert payload["validation"]["status"] == "ok"
        assert payload["authority_boundary"]["regenerates_control_packets"] is False
        assert payload["summary"]["wf85_status"] == "ready"
        assert payload["summary"]["pm_ready_job_count"] == 10
        assert payload["summary"]["tier_a_b_missing_decision_grade_band_tickers"] == ["ACN"]


def main() -> int:
    test_build_payload_from_existing_packets()
    print("startup brief packet tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
