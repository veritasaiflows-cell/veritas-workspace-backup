"""universe_consistency_check.py

Consistency gate to verify that downstream artifacts contain exactly the
tickers they are entitled to process, catching pipeline leakage or drops
before publication.

Usage:
    python scripts/universe_consistency_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import universe

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CONFIG_PATH = TMP / "portfolio-config.json"


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def get_record_tickers(payload: dict[str, Any] | None) -> set[str]:
    if not payload:
        return set()
    records = payload.get("records", [])
    if not isinstance(records, list):
        return set()
    return {r.get("ticker") for r in records if isinstance(r, dict) and r.get("ticker")}


def check_surface(name: str, actual: set[str], expected: set[str]) -> list[str]:
    errors = []
    missing = expected - actual
    extra = actual - expected
    if missing:
        errors.append(f"{name} is missing entitled tickers: {sorted(missing)}")
    if extra:
        errors.append(f"{name} contains unentitled tickers: {sorted(extra)}")
    return errors


def main() -> int:
    config = load_json(CONFIG_PATH)
    if not config:
        print(f"ERROR: Cannot load {CONFIG_PATH}")
        return 1

    tracked = config.get("tracked_universe") or {}
    
    expected_tech = universe.entitled_set(tracked, "technical_refresh")
    expected_trig = universe.entitled_set(tracked, "trigger_sheet")

    tech_payload = load_json(TMP / "technical-refresh.json")
    deploy_payload = load_json(TMP / "deployment-check.json")
    trig_payload = load_json(TMP / "trigger-sheet.json")

    all_errors = []

    if tech_payload is None:
        all_errors.append("technical-refresh.json is missing")
    else:
        all_errors.extend(check_surface("technical-refresh.json", get_record_tickers(tech_payload), expected_tech))

    if deploy_payload is None:
        all_errors.append("deployment-check.json is missing")
    else:
        all_errors.extend(check_surface("deployment-check.json", get_record_tickers(deploy_payload), expected_tech))

    if trig_payload is None:
        all_errors.append("trigger-sheet.json is missing")
    else:
        all_errors.extend(check_surface("trigger-sheet.json", get_record_tickers(trig_payload), expected_trig))

    from datetime import datetime, timezone
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if not all_errors else "error",
        "warnings": all_errors,
        "counts": {
            "tracked": len(tracked),
            "expected_tech": len(expected_tech),
            "expected_trig": len(expected_trig),
        }
    }
    (TMP / "universe-consistency.json").write_text(json.dumps(payload, indent=2), "utf-8")

    if all_errors:
        print("UNIVERSE CONSISTENCY FAILED:")
        for err in all_errors:
            print(f"  - {err}")
        return 0  # Return 0 so downstream validation can downgrade the dashboard visibly

    print("UNIVERSE CONSISTENCY OK: All ticker sets match lane entitlements.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
