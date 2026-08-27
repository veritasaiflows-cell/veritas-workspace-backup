from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_source_open_residue_classifier.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_source_open_residue_classifier", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.WF85_PACKET = module.TMP / "wf85-decision-os-review-packet.json"
    module.REPAIR_CONVEYOR = module.TMP / "trade-grade-repair-conveyor.json"
    module.TIER_ROUTER = module.TMP / "wf78-auto-tier-routing.json"
    module.SOURCE_REPAIR_EXECUTION = module.TMP / "wf78-source-open-repair-execution.json"
    module.SOURCE_WORK_PACKETS = module.TMP / "wf78-source-open-work-packets.json"
    module.LEGACY_ARCHIVE_CLOSEOUT = module.TMP / "legacy-42-full-archive-apply-closeout.json"
    module.LEGACY_NO_RUNTIME_IMPORTS = module.TMP / "legacy-42-no-runtime-imports-guard.json"
    module.OUT = module.TMP / "wf88-source-open-residue-classifier.json"
    module.MD_OUT = module.TMP / "wf88-source-open-residue-classifier.md"

    write_json(module.WF85_PACKET, {
        "status": "warning",
        "summary": {
            "implementation_blocker_count": 0,
            "source_open_status_counts": {"blocked": 4, "verified": 1},
        },
    })
    write_json(module.REPAIR_CONVEYOR, {
        "status": "ready_for_repair_execution",
        "rows": [
            {"ticker": "AAA", "source_open_status": "blocked", "decision_state": "blocked_missing_source_open", "repair_lane": "primary_state_blocker_repair"},
            {"ticker": "BBB", "source_open_status": "blocked", "decision_state": "below_stop_or_invalidation", "repair_lane": "invalidation_or_below_stop_review_only"},
            {"ticker": "CCC", "source_open_status": "blocked", "decision_state": "blocked_missing_source_open", "repair_lane": "primary_state_blocker_repair"},
            {"ticker": "DDD", "source_open_status": "blocked", "decision_state": "other", "repair_lane": "other"},
        ],
    })
    write_json(module.TIER_ROUTER, {
        "status": "ok",
        "summary": {
            "active_ticker_count": 4,
            "auto_tier_counts": {"Tier A": 1, "Tier B": 1, "Tier C": 1},
            "production_adjudication_deprecated_for_authority": True,
            "tier_a_packet_deprecated_for_authority": True,
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
        },
        "rows": [
            {"ticker": "AAA", "auto_tier": "Tier A", "auto_state": "A-WATCH", "capital_deployment_approved": False, "trade_or_execution_approved": False},
            {"ticker": "BBB", "auto_tier": "Tier A", "auto_state": "A-WATCH", "capital_deployment_approved": False, "trade_or_execution_approved": False},
            {"ticker": "CCC", "auto_tier": "Tier C", "auto_state": "C-MONITOR", "capital_deployment_approved": False, "trade_or_execution_approved": False},
            {"ticker": "DDD", "auto_tier": "Tier Z", "auto_state": "legacy", "capital_deployment_approved": False, "trade_or_execution_approved": False},
        ],
    })
    write_json(module.SOURCE_REPAIR_EXECUTION, {"status": "ok", "summary": {"priority_tickers": ["AAA"]}})
    write_json(module.SOURCE_WORK_PACKETS, {"status": "ok", "packets": []})
    write_json(module.LEGACY_ARCHIVE_CLOSEOUT, {"status": "archived"})
    write_json(module.LEGACY_NO_RUNTIME_IMPORTS, {"status": "ok", "summary": {"active_runtime_blocker_count": 0}})


def test_classifier_splits_source_open_rows_without_runtime_drag() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["source_open_blocked_count"] == 4
        assert packet["summary"]["default_runtime_blocker_count"] == 0
        assert packet["summary"]["implementation_blocker_count"] == 0
        assert packet["summary"]["active_sql_json_tier_repair_count"] == 1
        assert packet["summary"]["below_stop_or_invalidation_review_only_count"] == 1
        assert packet["summary"]["monitor_only_context_count"] == 1
        assert packet["summary"]["legacy_42_deprecated_residue_count"] == 1
        assert packet["authority_boundary"]["delete_allowed"] is False


if __name__ == "__main__":
    test_classifier_splits_source_open_rows_without_runtime_drag()
    print("wf88 source-open residue classifier tests passed")
