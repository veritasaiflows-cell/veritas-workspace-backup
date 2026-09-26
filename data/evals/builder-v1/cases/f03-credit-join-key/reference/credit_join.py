import json


def _key(sub):
    try:
        payload = json.loads(sub.get("payload_json") or "{}")
    except ValueError:
        payload = None
    key = payload.get("taskRunId") if isinstance(payload, dict) else None
    return key or sub.get("run_id")


def join_runs(tasks, subs):
    """Pair each task row with its registry row.

    tasks: list of {"task_id", "run_id"}; subs: list of {"run_id", "payload_json"}.
    Returns {task_id: sub | None | "AMBIGUOUS"}.
    """
    groups = {}
    for sub in subs:
        groups.setdefault(_key(sub), []).append(sub)
    out = {}
    for task in tasks:
        found = groups.get(task["run_id"], [])
        out[task["task_id"]] = None if not found else found[0] if len(found) == 1 else "AMBIGUOUS"
    return out
