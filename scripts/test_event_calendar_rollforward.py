from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import event_calendar_rollforward as rollforward


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_rollforward_stages_stale_vault_date_with_unconfirmed_provider_label(tmp_path: Path, errors: list[str]) -> None:
    earnings = {
        "generated_at_utc": "2026-05-10T16:00:00+00:00",
        "status": "ok",
        "stale_after_days": 7,
        "records": [
            {"ticker": "ETN", "next_earnings_date": "2026-08-04", "source": "yfinance", "fetched_at_utc": "2026-05-10T16:00:00+00:00"},
            {"ticker": "NVDA", "next_earnings_date": "2026-05-20", "source": "yfinance", "fetched_at_utc": "2026-05-10T16:00:00+00:00"},
        ],
    }
    config = {
        "tracked_universe": {
            "ETN": {"coverage_lane": "execution", "portfolio_role": "tactical"},
            "NVDA": {"coverage_lane": "execution", "portfolio_role": "core"},
        },
        "earnings_date_watchlist": {
            "NVDA": {"date": "2026-05-20", "primary_confirmed": False},
        },
    }
    calendar = """# Event Calendar

## May 2026

| Date | Day | Event | Priority | Notes |
|---|---|---|---|---|
| May 5 | Tue | **ETN Q1 2026 Earnings — Reported / Interpreted** | **[CRITICAL]** | Closed with follow-up. |
| May 20 | Wed | **NVDA Q1 2026 Earnings — likely / unconfirmed** | **[CRITICAL]** | Keep timing caution. |
"""

    earnings_path = tmp_path / "tmp" / "earnings-calendar.json"
    config_path = tmp_path / "tmp" / "portfolio-config.json"
    event_path = tmp_path / "05. Intelligence" / "Event Calendar.md"
    out_json = tmp_path / "tmp" / "event-calendar-rollforward.json"
    out_md = tmp_path / "tmp" / "event-calendar-rollforward.md"
    _write_json(earnings_path, earnings)
    _write_json(config_path, config)
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.write_text(calendar, encoding="utf-8")

    old_paths = (
        rollforward.WORKSPACE,
        rollforward.EARNINGS_PATH,
        rollforward.CONFIG_PATH,
        rollforward.SOURCE_CONFIDENCE_PATH,
        rollforward.EVENT_CALENDAR_PATH,
        rollforward.OUT_JSON,
        rollforward.OUT_MD,
    )
    try:
        rollforward.WORKSPACE = tmp_path
        rollforward.EARNINGS_PATH = earnings_path
        rollforward.CONFIG_PATH = config_path
        rollforward.SOURCE_CONFIDENCE_PATH = tmp_path / "tmp" / "earnings-date-source-confidence.json"
        rollforward.EVENT_CALENDAR_PATH = event_path
        rollforward.OUT_JSON = out_json
        rollforward.OUT_MD = out_md
        rollforward.main()
    finally:
        (
            rollforward.WORKSPACE,
            rollforward.EARNINGS_PATH,
            rollforward.CONFIG_PATH,
            rollforward.SOURCE_CONFIDENCE_PATH,
            rollforward.EVENT_CALENDAR_PATH,
            rollforward.OUT_JSON,
            rollforward.OUT_MD,
        ) = old_paths

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    proposals = {row["ticker"]: row for row in payload["proposals"]}
    if proposals.get("ETN", {}).get("vault_date") != "2026-05-05":
        errors.append(f"ETN vault_date mismatch: {proposals.get('ETN')}")
    if proposals.get("ETN", {}).get("provider_next_earnings_date") != "2026-08-04":
        errors.append(f"ETN provider date mismatch: {proposals.get('ETN')}")
    if proposals.get("ETN", {}).get("confidence") != "provider_estimate_unconfirmed":
        errors.append(f"ETN confidence should be provider_estimate_unconfirmed: {proposals.get('ETN')}")
    if proposals.get("ETN", {}).get("recommended_action") != "roll_forward_review":
        errors.append(f"ETN action should be roll_forward_review: {proposals.get('ETN')}")
    if "NVDA" in proposals:
        errors.append("matching active timing baseline should not create a stale-date roll-forward")
    if "provider_estimate_unconfirmed" not in out_md.read_text(encoding="utf-8"):
        errors.append("markdown output should preserve provider_estimate_unconfirmed label")


def main() -> int:
    errors: list[str] = []
    with TemporaryDirectory() as tmp:
        test_rollforward_stages_stale_vault_date_with_unconfirmed_provider_label(Path(tmp), errors)
    if errors:
        print("event_calendar_rollforward_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("event_calendar_rollforward_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
