import hashlib


def task_hash(text):
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def matches(record, stored_task):
    return record["sha256"] == task_hash(stored_task)
