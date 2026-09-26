def decide(trigger, signature):
    """Fire once per new signature. Returns (fire, new_state)."""
    raw = trigger.get("state")
    state = raw if isinstance(raw, dict) else {}
    prev_count = state.get("fired_count")
    if not isinstance(prev_count, int):
        prev_count = 0
    if state.get("signature") == signature:
        return False, {"signature": signature, "fired_count": prev_count}
    return True, {"signature": signature, "fired_count": prev_count + 1}
