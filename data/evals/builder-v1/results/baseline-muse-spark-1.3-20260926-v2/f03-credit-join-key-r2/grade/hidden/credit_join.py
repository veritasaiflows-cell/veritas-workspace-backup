import json


def _join_key(sub):
    """True join key for a registry row.

    Uses ``taskRunId`` from ``payload_json`` when it is a JSON string
    encoding an object with a usable ``taskRunId``; otherwise falls back
    to the row's ``run_id``.
    """
    fallback = sub.get("run_id")
    if "payload_json" not in sub:
        return fallback
    pj = sub.get("payload_json")
    if pj is None:
        return fallback
    if isinstance(pj, dict):
        parsed = pj
    else:
        if not isinstance(pj, str):
            return fallback
        if pj.strip() == "":
            return fallback
        try:
            parsed = json.loads(pj)
        except (ValueError, TypeError):
            return fallback
        if not isinstance(parsed, dict):
            return fallback
    if "taskRunId" not in parsed:
        return fallback
    val = parsed["taskRunId"]
    if val is None:
        return fallback
    if isinstance(val, str) and val == "":
        return fallback
    try:
        hash(val)
    except TypeError:
        return fallback
    return val


def join_runs(tasks, subs):
    """Pair each task row with its registry row.

    tasks: list of {"task_id", "run_id"}; subs: list of {"run_id", "payload_json"}.
    Returns {task_id: sub | None | "AMBIGUOUS"}.
    """
    grouped = {}
    for s in subs:
        grouped.setdefault(_join_key(s), []).append(s)
    result = {}
    for t in tasks:
        matches = grouped.get(t["run_id"], [])
        if len(matches) == 0:
            result[t["task_id"]] = None
        elif len(matches) == 1:
            result[t["task_id"]] = matches[0]
        else:
            result[t["task_id"]] = "AMBIGUOUS"
    return result
