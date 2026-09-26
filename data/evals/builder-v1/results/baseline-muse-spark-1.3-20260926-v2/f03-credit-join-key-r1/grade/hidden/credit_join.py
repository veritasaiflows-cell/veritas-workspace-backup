import json


def _join_key(sub):
    """Extract the true join key for a registry row.

    Prefers ``taskRunId`` from the row's ``payload_json`` (a JSON string);
    falls back to the row's ``run_id`` when ``payload_json`` is missing,
    empty, not valid JSON, not a JSON object, or has no ``taskRunId``.
    """
    fallback = sub.get("run_id")
    if "payload_json" not in sub:
        return fallback
    payload = sub["payload_json"]
    if payload is None:
        return fallback
    if not isinstance(payload, str):
        return fallback
    if payload.strip() == "":
        return fallback
    try:
        obj = json.loads(payload)
    except (json.JSONDecodeError, ValueError, TypeError):
        return fallback
    if not isinstance(obj, dict):
        return fallback
    if "taskRunId" not in obj:
        return fallback
    task_run_id = obj["taskRunId"]
    if task_run_id is None:
        return fallback
    if isinstance(task_run_id, str) and task_run_id == "":
        return fallback
    return task_run_id


def join_runs(tasks, subs):
    """Pair each task row with its registry row.

    tasks: list of {"task_id", "run_id"}; subs: list of {"run_id", "payload_json"}.
    Returns {task_id: sub | None | "AMBIGUOUS"}.

    The join key for a registry row is ``taskRunId`` inside ``payload_json``
    (falling back to ``run_id`` per :func:`_join_key`). A task whose ``run_id``
    matches no registry row maps to ``None``; a task matched by two or more
    registry rows maps to ``"AMBIGUOUS"``.
    """
    grouped = {}
    for s in subs:
        key = _join_key(s)
        grouped.setdefault(key, []).append(s)
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
