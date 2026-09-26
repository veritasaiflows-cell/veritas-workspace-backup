"""Evaluate a cron trigger from an exec() result."""
import json


def parse_exec_result(res):
    """Return the parsed JSON object the command printed, or None."""
    text = res.get("stdout") or res.get("output") or res.get("text") or res.get("aggregated")
    if not text:
        return None
    if not isinstance(text, str):
        return None
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    candidate = lines[-1] if lines else ""
    if not candidate:
        return None
    try:
        doc = json.loads(candidate)
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
