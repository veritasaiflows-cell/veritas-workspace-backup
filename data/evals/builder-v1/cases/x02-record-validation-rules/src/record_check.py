REQUIRED = ("dispatch_id", "agent_id", "session_key", "label")


def validate(record):
    """Return a list of error strings; empty means valid."""
    errors = []
    for key in REQUIRED:
        if not record.get(key):
            errors.append(f"missing:{key}")
    return errors
