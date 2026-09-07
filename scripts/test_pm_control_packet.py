#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pm_control_packet.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pm_control_packet_alerts_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_retired_finance_route_projection() -> None:
    module = load_module()
    source = {
        "authority_boundary": {
            "canon_or_portfolio_mutation_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
        },
        "jobs": [
            {"job_id": "runtime-safe", "title": "Refresh runtime proof"},
            {"job_id": "wf87-readiness", "title": "Keep old route visible"},
            {"job_id": "trade-grade-card", "command": "scripts/trade-grade-decision-cards.py"},
        ],
        "wf78_owner_card_prep_loop": {"path": "tmp/wf78-owner-card-prep-loop.json"},
    }
    projected = module.strip_retired_finance_routes(source)
    assert projected["jobs"] == [{"job_id": "runtime-safe", "title": "Refresh runtime proof"}]
    assert "wf78_owner_card_prep_loop" not in projected
    assert projected["authority_boundary"]["canon_or_portfolio_mutation_allowed"] is False
    assert projected["authority_boundary"]["capital_deployment_allowed"] is False
    assert projected["authority_boundary"]["paper_or_live_execution_allowed"] is False


def test_alerts_os_health_uses_only_current_proofs() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        module.ROOT = tmp.parent
        module.TMP = tmp
        module.FINANCE_SQL_GUARD = tmp / "finance-sql-canon-access-validation.json"
        module.ALERT_QUOTE_PROOF = tmp / "intraday-alerts" / "quote-snapshot-proof.json"
        module.ALERT_FRESHNESS_CONTROLLER = tmp / "alert-level-freshness-controller.json"
        module.ALERT_RECOMMENDATIONS_DIGEST = tmp / "finance-alert-os-digest.json"
        module.ALERTS_OS_PIVOT_VALIDATOR = tmp / "alerts-os-pivot-validator.json"
        for path in (
            module.FINANCE_SQL_GUARD,
            module.ALERT_QUOTE_PROOF,
            module.ALERT_FRESHNESS_CONTROLLER,
            module.ALERT_RECOMMENDATIONS_DIGEST,
            module.ALERTS_OS_PIVOT_VALIDATOR,
        ):
            write_json(path, {
                "status": "ok",
                "generated_at_utc": "2026-08-30T05:00:00Z",
                "summary": {"ticker_count": 18, "alert_state_counts": {"monitor_only": 18}},
                "validation": {"status": "ok"},
            })
        payload = module.alerts_os_health(datetime(2026, 8, 30, 5, 30, tzinfo=timezone.utc))
        assert payload["status"] == "ok"
        assert payload["blocked_proofs"] == []
        assert payload["ticker_count"] == 18
        assert set(payload["proofs"]) == {
            "sql_guard", "quote_snapshot", "freshness_controller", "recommendations_digest", "pivot_validator"
        }
        write_json(module.ALERTS_OS_PIVOT_VALIDATOR, {"status": "error", "validation": {"status": "error"}})
        blocked = module.alerts_os_health(datetime(2026, 8, 30, 5, 30, tzinfo=timezone.utc))
        assert blocked["status"] == "blocked"
        assert blocked["blocked_proofs"] == ["pivot_validator"]


def main() -> int:
    test_retired_finance_route_projection()
    test_alerts_os_health_uses_only_current_proofs()
    print("pm_control_packet alerts OS tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
