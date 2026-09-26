"""Evaluate a cron trigger from an exec() result."""
import json


def parse_exec_result(res):
    """Return the parsed JSON object the command printed, or None."""
    text = res.get("aggregated")
    if text is None:
        text = res.get("stdout") or res.get("output") or res.get("text")
    if not text or not isinstance(text, str):
        return None
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
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
