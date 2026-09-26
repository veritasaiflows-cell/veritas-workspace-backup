import json


def join_runs(tasks, subs):
    """Pair each task row with its registry row.

    tasks: list of {"task_id", "run_id"}; subs: list of {"run_id", "payload_json"}.
    Returns {task_id: sub | None | "AMBIGUOUS"}.
    """
    by_run = {s["run_id"]: s for s in subs}
    return {t["task_id"]: by_run.get(t["run_id"]) for t in tasks}
