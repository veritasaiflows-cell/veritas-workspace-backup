from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
EARNINGS_CALENDAR = ROOT / "tmp" / "earnings-calendar.json"
BLOCKED_DAYS = 7
WARNING_DAYS = 14


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def find_record(data: Dict[str, Any], ticker: str) -> Dict[str, Any] | None:
    for record in data.get("records", []):
        if record.get("ticker") == ticker:
            return record
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check earnings catalyst window for a candidate packet.")
    parser.add_argument("packet", help="Path to candidate packet JSON")
    args = parser.parse_args()

    packet = load_json(Path(args.packet))
    ticker = packet["ticker"]
    calendar = load_json(EARNINGS_CALENDAR)
    record = find_record(calendar, ticker)
    if record is None or not record.get("next_earnings_date"):
        result = {"ok": False, "status": "unknown", "blockers": ["earnings date missing from earnings-calendar"]}
        print(json.dumps(result, indent=2))
        return 1

    today = date.fromisoformat(calendar.get("as_of_date"))
    earnings_date = date.fromisoformat(record["next_earnings_date"])
    days_until = (earnings_date - today).days
    if days_until < 0:
        status = "clear"
    elif days_until <= BLOCKED_DAYS:
        status = "blocked"
    elif days_until <= WARNING_DAYS:
        status = "warning"
    else:
        status = "clear"

    blockers = []
    if status == "blocked":
        blockers.append(f"earnings in {days_until} days")
    result = {
        "ok": status == "clear",
        "ticker": ticker,
        "as_of_date": today.isoformat(),
        "next_earnings_date": earnings_date.isoformat(),
        "days_until_earnings": days_until,
        "status": status,
        "blockers": blockers,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
