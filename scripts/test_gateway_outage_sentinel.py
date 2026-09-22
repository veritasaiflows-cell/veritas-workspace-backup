"""Tests for gateway_outage_sentinel gap classification (G8 restart guard)."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gateway_outage_sentinel as s

U = timezone.utc


def expect(name: str, cond: bool) -> int:
    print(("-", "PASS" if cond else "FAIL", name))
    return 0 if cond else 1


def main() -> int:
    rc = 0
    # 1. Overnight gap (00:00-02:00 PHX) on a declared day: risk, not voiding.
    cls, voiding, overnight, _ = s.classify_gap(datetime(2026, 9, 21, 7, 0, tzinfo=U), datetime(2026, 9, 21, 9, 0, tzinfo=U))
    rc |= expect("overnight gap on declared day classifies overnight_risk", cls == "overnight_risk" and not voiding)
    # 2. Observation-hours gap (06:30-07:00 PHX) on a declared day: voiding.
    cls, voiding, _, _ = s.classify_gap(datetime(2026, 9, 21, 13, 30, tzinfo=U), datetime(2026, 9, 21, 14, 0, tzinfo=U))
    rc |= expect("observation-hours gap on declared day classifies voiding", cls == "voiding" and voiding[0]["date"] == "2026-09-21")
    # 3. Same gap on the closed-market observation day (09-20): not voiding.
    cls, _, _, obs_day = s.classify_gap(datetime(2026, 9, 20, 13, 30, tzinfo=U), datetime(2026, 9, 20, 14, 0, tzinfo=U))
    rc |= expect("observation-day gap flags obs day without voiding", cls == "benign" and obs_day is True)
    # 4. Evening gap outside all windows: benign.
    cls, _, _, _ = s.classify_gap(datetime(2026, 9, 19, 3, 0, tzinfo=U), datetime(2026, 9, 19, 4, 0, tzinfo=U))
    rc |= expect("evening gap classifies benign", cls == "benign")
    # 5. Boundary: gap 12:59-13:30 PHX on declared day still overlaps the window by 1 minute.
    cls, voiding, _, _ = s.classify_gap(datetime(2026, 9, 22, 19, 59, tzinfo=U), datetime(2026, 9, 22, 20, 30, tzinfo=U))
    rc |= expect("boundary overlap 12:59-13:00 counts as voiding", cls == "voiding" and voiding[0]["observation_overlap_minutes"] == 1.0)
    # 6. Gap crossing midnight into a declared day's observation window.
    cls, voiding, overnight, _ = s.classify_gap(datetime(2026, 9, 21, 12, 0, tzinfo=U), datetime(2026, 9, 21, 17, 0, tzinfo=U))
    rc |= expect("gap spanning night-into-observation voids and records overnight", cls == "voiding" and overnight)
    print("PASS" if rc == 0 else "FAIL", "gateway_outage_sentinel classification")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())