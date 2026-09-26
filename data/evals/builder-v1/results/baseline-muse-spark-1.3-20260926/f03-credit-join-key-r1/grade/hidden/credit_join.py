import json


def _join_key(sub):
    """True join key for a registry row.

    Uses taskRunId from payload_json when present; otherwise the row's run_id.
    """
    fallback = sub.get("run_id")
    raw = sub.get("payload_json")
    if not isinstance(raw, str) or not raw.strip():
        return fallback
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return fallback
    if not isinstance(parsed, dict):
        return fallback
    task_run_id = parsed.get("taskRunId")
    if not isinstance(task_run_id, str) or not task_run_id:
        return fallback
    return task_run_id


def join_runs(tasks, subs):
    """Pair each task row with its registry row.

    tasks: list of {"task_id", "run_id"}; subs: list of {"run_id", "payload_json"}.
    Returns {task_id: sub | None | "AMBIGUOUS"}.
    """
    by_key = {}
    for s in subs:
        by_key.setdefault(_join_key(s), []).append(s)
    result = {}
    for t in tasks:
        matches = by_key.get(t["run_id"], [])
        if not matches:
            result[t["task_id"]] = None
        elif len(matches) == 1:
            result[t["task_id"]] = matches[0]
        else:
            result[t["task_id"]] = "AMBIGUOUS"
    return result
