REQUIRED = ("dispatch_id", "agent_id", "session_key", "label")


def _present(record, key):
    value = record.get(key)
    return bool(value.strip()) if isinstance(value, str) else bool(value)


def validate(record):
    """Return a list of error strings; empty means valid."""
    errors = [f"missing:{key}" for key in REQUIRED if not _present(record, key)]
    if _present(record, "agent_id") and _present(record, "session_key"):
        prefix = f"agent:{record['agent_id']}:"
        key = record["session_key"]
        if not (key.startswith(prefix) and len(key) > len(prefix)):
            errors.append("session_key_not_scoped")
    if "created_at_ms" in record:
        value = record["created_at_ms"]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            errors.append("bad_created_at")
    return errors
