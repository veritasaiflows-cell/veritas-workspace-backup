"""Evaluate a cron trigger from an exec() result."""
import json


def parse_exec_result(res):
    """Return the parsed JSON object the command printed, or None."""
    text = res.get("aggregated")
    if not text:
        return None
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        doc = json.loads(lines[-1])
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def should_fire(res):
    doc = parse_exec_result(res)
    if doc is None:
        return {"fire": True, "reason": "unreadable"}
    if doc.get("actionable", 0) > 0:
        return {"fire": True, "reason": "actionable"}
    return {"fire": False, "reason": "quiet"}
