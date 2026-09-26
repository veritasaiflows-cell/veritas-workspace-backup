import json
import os
from datetime import date, timedelta


def coverage(dir_path):
    """Summarize price snapshot files (*.json) in dir_path."""
    files = [name for name in os.listdir(dir_path) if name.endswith(".json")]

    dates = set()
    for name in files:
        try:
            with open(os.path.join(dir_path, name), "r") as fh:
                obj = json.load(fh)
        except (OSError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        data_date = obj.get("data_date")
        if not isinstance(data_date, str):
            continue
        dates.add(data_date)

    parsed = set()
    for s in dates:
        try:
            y, m, d = s.split("-")
            parsed.add(date(int(y), int(m), int(d)))
        except (ValueError, AttributeError):
            continue

    gaps = []
    if len(parsed) >= 2:
        covered = {d.isoformat() for d in parsed}
        earliest = min(parsed)
        latest = max(parsed)
        current = earliest + timedelta(days=1)
        while current < latest:
            if current.weekday() < 5 and current.isoformat() not in covered:
                gaps.append(current.isoformat())
            current += timedelta(days=1)
        gaps.sort()

    return {"snapshots": len(files), "days": len(dates), "gaps": gaps}
