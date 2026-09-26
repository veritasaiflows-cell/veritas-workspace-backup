"""Evaluate a cron trigger from an exec() result."""
import json


def parse_exec_result(res):
    """Return the parsed JSON object the command printed, or None."""
    if not isinstance(res, dict):
        return None
    text = res.get("stdout") or res.get("output") or res.get("text") or res.get("aggregated")
    if not text or not isinstance(text, str):
        return None
    last = ""
    for line in text.splitlines():
        if line.strip():
            last = line
    last = last.strip()
    if not last:
        return None
    try:
        doc = json.loads(last)
    except (ValueError, TypeError):
        return None
    return doc if isinstance(doc, dict) else None


def should_fire(res):
    doc = parse_exec_result(res)
    if doc is None:
        return {"fire": True, "reason": "unreadable"}
    if doc.get("actionable", 0) > 0:
        return {"fire": True, "reason": "actionable"}
    return {"fire": False, "reason": "quiet"}
