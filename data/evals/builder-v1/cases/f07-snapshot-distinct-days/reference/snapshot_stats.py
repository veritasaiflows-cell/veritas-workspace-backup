import json
import os
from datetime import date, timedelta


def coverage(dir_path):
    """Summarize price snapshot files (*.json) in dir_path."""
    files = [name for name in os.listdir(dir_path) if name.endswith(".json")]
    dates = set()
    for name in files:
        try:
            with open(os.path.join(dir_path, name), encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and isinstance(doc.get("data_date"), str):
            dates.add(doc["data_date"])
    gaps = []
    if len(dates) >= 2:
        parsed = sorted(date.fromisoformat(item) for item in dates)
        have = set(parsed)
        day = parsed[0] + timedelta(days=1)
        while day < parsed[-1]:
            if day.weekday() < 5 and day not in have:
                gaps.append(day.isoformat())
            day += timedelta(days=1)
    return {"snapshots": len(files), "days": len(dates), "gaps": gaps}
