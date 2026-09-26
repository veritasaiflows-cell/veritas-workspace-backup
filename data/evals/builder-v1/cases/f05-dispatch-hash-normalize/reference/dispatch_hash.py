import hashlib


def normalize(text):
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def task_hash(text):
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def matches(record, stored_task):
    return record["sha256"] == task_hash(stored_task)
