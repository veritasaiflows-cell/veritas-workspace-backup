import hashlib


def task_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def matches(record, stored_task):
    return record["sha256"] == task_hash(stored_task)
