#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
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


def test_alerts_os_health_accepts_sent_validated_digest() -> None:
    """A sent (delivered, validated) digest is proof, not a failure.

    Regression: alerts_os_health required status == ok for every proof, so a
    successfully sent digest (status=sent, validation=ok) blocked the PM
    packet and the weekly radar proof sequence. send_failed and blocked digests
    must stay blocking.
    """
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
            module.ALERTS_OS_PIVOT_VALIDATOR,
        ):
            write_json(path, {
                "status": "ok",
                "generated_at_utc": "2026-09-07T05:00:00Z",
                "summary": {"ticker_count": 18},
                "validation": {"status": "ok"},
            })
        # 2026-09-07 05:30 UTC is Sunday 22:30 Phoenix, so the weekly digest
        # slot (Sunday 08:00 + 1h grace) is due and its per-mode proof is
        # required alongside the global digest proof.
        write_json(tmp / "finance-alert-os-weekly-digest.json", {
            "status": "sent",
            "generated_at_utc": "2026-09-07T05:00:00Z",
            "validation": {"status": "ok"},
        })
        for digest_status in ("ok", "weekend_quiet", "duplicate_quiet", "sent"):
            write_json(module.ALERT_RECOMMENDATIONS_DIGEST, {
                "status": digest_status,
                "generated_at_utc": "2026-09-07T05:00:00Z",
                "summary": {"ticker_count": 18},
                "validation": {"status": "ok"},
            })
            payload = module.alerts_os_health(datetime(2026, 9, 7, 5, 30, tzinfo=timezone.utc))
            assert payload["status"] == "ok", digest_status
            assert payload["blocked_proofs"] == [], digest_status
        for digest_status in ("blocked", "send_failed", "error"):
            write_json(module.ALERT_RECOMMENDATIONS_DIGEST, {
                "status": digest_status,
                "generated_at_utc": "2026-09-07T05:00:00Z",
                "summary": {"ticker_count": 18},
                "validation": {"status": "ok" if digest_status == "send_failed" else "error"},
            })
            payload = module.alerts_os_health(datetime(2026, 9, 7, 5, 30, tzinfo=timezone.utc))
            assert payload["status"] == "blocked", digest_status
            assert payload["blocked_proofs"] == ["recommendations_digest"], digest_status


def test_alerts_os_health_blocks_stale_structurally_valid_proofs() -> None:
    """A structurally valid proof older than its age threshold blocks (finding 2).

    Regression: alerts_os_health accepted proofs on structural validity alone,
    so a dead producer leaving yesterday's artifact behind still passed. Age
    thresholds must block stale proofs while market-window grace suppresses the
    intraday-chain checks on weekends, holidays, and pre-refresh.
    """
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
                "generated_at_utc": "2026-09-08T19:00:00Z",
                "summary": {"ticker_count": 18},
                "validation": {"status": "ok"},
            })
        # Tuesday 13:00 Phoenix: no market grace, weekday digest modes due.
        now = datetime(2026, 9, 8, 20, 0, tzinfo=timezone.utc)
        due = module.due_digest_mode_slots(now)
        assert set(due) == {"morning", "recommendations", "midday"}
        for mode in due:
            write_json(tmp / f"finance-alert-os-{mode}-digest.json", {
                "status": "sent",
                "generated_at_utc": "2026-09-08T19:00:00Z",
                "validation": {"status": "ok"},
            })
        stale = now - timedelta(hours=40)
        os.utime(module.FINANCE_SQL_GUARD, (stale.timestamp(), stale.timestamp()))
        payload = module.alerts_os_health(now)
        assert payload["status"] == "blocked"
        assert payload["blocked_proofs"] == ["sql_guard"]
        assert payload["proofs"]["sql_guard"]["age_stale"] is True
        # Sunday 15:00 Phoenix: the same 40h-old sql_guard proof is stale by
        # age but weekend grace suppresses the threshold, and only the weekly
        # digest slot is due.
        grace_now = datetime(2026, 9, 6, 22, 0, tzinfo=timezone.utc)
        assert set(module.due_digest_mode_slots(grace_now)) == {"weekly"}
        write_json(tmp / "finance-alert-os-weekly-digest.json", {
            "status": "sent",
            "generated_at_utc": "2026-09-06T21:00:00Z",
            "validation": {"status": "ok"},
        })
        stale_for_grace = grace_now - timedelta(hours=40)
        os.utime(module.FINANCE_SQL_GUARD, (stale_for_grace.timestamp(), stale_for_grace.timestamp()))
        payload = module.alerts_os_health(grace_now)
        assert payload["status"] == "ok"
        assert payload["proofs"]["sql_guard"]["age_stale"] is False
        assert payload["proofs"]["sql_guard"]["age_grace_suppressed"] is True


def test_alerts_os_health_blocks_masked_failed_digest_mode() -> None:
    """A later digest mode's success must not hide an earlier mode's failure (finding 3).

    Regression: the global digest proof is last-writer-wins, so the successful
    midday send on 2026-09-14 overwrote the failed morning Telegram digest and
    alerts_os_health reported ok. Each due mode must show its own per-mode
    proof, written after its slot, with an acceptable status.
    """
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
                "generated_at_utc": "2026-09-14T20:00:00Z",
                "summary": {"ticker_count": 18},
                "validation": {"status": "ok"},
            })
        # Monday 14:00 Phoenix: morning, recommendations, and midday due;
        # post-close (13:20 + 1h grace) is not yet due.
        now = datetime(2026, 9, 14, 21, 0, tzinfo=timezone.utc)
        assert set(module.due_digest_mode_slots(now)) == {"morning", "recommendations", "midday"}
        # The global proof shows the successful midday send, but the morning
        # per-mode proof retains its failed delivery from 06:05.
        write_json(tmp / "finance-alert-os-morning-digest.json", {
            "status": "send_failed",
            "generated_at_utc": "2026-09-14T13:05:00Z",
            "validation": {"status": "ok"},
        })
        write_json(tmp / "finance-alert-os-recommendations-digest.json", {
            "status": "sent",
            "generated_at_utc": "2026-09-14T20:00:00Z",
            "validation": {"status": "ok"},
        })
        write_json(tmp / "finance-alert-os-midday-digest.json", {
            "status": "sent",
            "generated_at_utc": "2026-09-14T20:15:00Z",
            "validation": {"status": "ok"},
        })
        payload = module.alerts_os_health(now)
        assert payload["status"] == "blocked"
        assert "digest_mode_morning" in payload["blocked_proofs"]
        assert payload["blocked_digest_modes"] == ["morning"]
        # Recovery: the morning mode's own proof validates again.
        write_json(tmp / "finance-alert-os-morning-digest.json", {
            "status": "sent",
            "generated_at_utc": "2026-09-14T20:30:00Z",
            "validation": {"status": "ok"},
        })
        payload = module.alerts_os_health(now)
        assert payload["status"] == "ok"
        assert payload["blocked_digest_modes"] == []


def main() -> int:
    test_retired_finance_route_projection()
    test_alerts_os_health_uses_only_current_proofs()
    test_alerts_os_health_accepts_sent_validated_digest()
    test_alerts_os_health_blocks_stale_structurally_valid_proofs()
    test_alerts_os_health_blocks_masked_failed_digest_mode()
    print("pm_control_packet alerts OS tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
