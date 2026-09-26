REQUIRED = ("dispatch_id", "agent_id", "session_key", "label")


def validate(record):
    """Return a list of error strings; empty means valid."""
    errors = []
    for key in REQUIRED:
        val = record.get(key)
        if not val:
            errors.append(f"missing:{key}")
        elif key == "label" and isinstance(val, str) and not val.strip():
            errors.append("missing:label")
    agent_id = record.get("agent_id")
    session_key = record.get("session_key")
    if agent_id and session_key:
        prefix = f"agent:{agent_id}:"
        if not (
            isinstance(agent_id, str)
            and isinstance(session_key, str)
            and session_key.startswith(prefix)
            and len(session_key) > len(prefix)
        ):
            errors.append("session_key_not_scoped")
    if "created_at_ms" in record:
        created_at_ms = record["created_at_ms"]
        if type(created_at_ms) is not int or created_at_ms <= 0:
            errors.append("bad_created_at")
    return errors
