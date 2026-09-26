import json
import os
from datetime import date, timedelta


def _parse_data_date(value):
    if not isinstance(value, str):
        return None
    try:
        year, month, day = map(int, value.split("-"))
        return date(year, month, day)
    except (ValueError, AttributeError):
        return None


def coverage(dir_path):
    """Summarize price snapshot files (*.json) in dir_path."""
    files = [name for name in os.listdir(dir_path) if name.endswith(".json")]
    distinct = set()
    for name in files:
        path = os.path.join(dir_path, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                obj = json.load(fh)
        except (OSError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        parsed = _parse_data_date(obj.get("data_date"))
        if parsed is None:
            continue
        distinct.add(parsed.isoformat())
    if len(distinct) < 2:
        gaps = []
    else:
        present = set(distinct)
        earliest = min(present)
        latest = max(present)
        start = date.fromisoformat(earliest)
        end = date.fromisoformat(latest)
        gaps = []
        current = start + timedelta(days=1)
        while current < end:
            if current.weekday() < 5 and current.isoformat() not in present:
                gaps.append(current.isoformat())
            current += timedelta(days=1)
        gaps.sort()
    return {"snapshots": len(files), "days": len(distinct), "gaps": gaps}
