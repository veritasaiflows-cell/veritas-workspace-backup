import json


def _join_key(row):
    """True join key: taskRunId inside payload_json, else row run_id."""
    fallback = row.get("run_id") if isinstance(row, dict) else None
    payload = row.get("payload_json") if isinstance(row, dict) else None
    if payload is None:
        return fallback
    if isinstance(payload, dict):
        obj = payload
    elif isinstance(payload, str):
        if payload.strip() == "":
            return fallback
        try:
            obj = json.loads(payload)
        except (ValueError, TypeError):
            return fallback
        if not isinstance(obj, dict):
            return fallback
    else:
        return fallback
    if "taskRunId" not in obj or obj["taskRunId"] is None:
        return fallback
    return obj["taskRunId"]


def join_runs(tasks, subs):
    """Pair each task row with its registry row.

    tasks: list of {"task_id", "run_id"}; subs: list of {"run_id", "payload_json"}.
    Returns {task_id: sub | None | "AMBIGUOUS"}.
    """
    grouped = {}
    for s in subs:
        grouped.setdefault(_join_key(s), []).append(s)
    out = {}
    for t in tasks:
        matches = grouped.get(t.get("run_id"), [])
        if len(matches) == 0:
            out[t.get("task_id")] = None
        elif len(matches) == 1:
            out[t.get("task_id")] = matches[0]
        else:
            out[t.get("task_id")] = "AMBIGUOUS"
    return out
