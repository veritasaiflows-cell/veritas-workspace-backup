def truncate_message(text, limit=4096):
    """Return text unchanged if it fits; otherwise cut it so the result, including a
    trailing "…", is exactly `limit` characters."""
    if len(text) <= limit:
        return text
    return text[:limit] + "…"
