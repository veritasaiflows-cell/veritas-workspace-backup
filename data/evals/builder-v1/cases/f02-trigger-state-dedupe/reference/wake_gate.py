def decide(trigger, signature):
    """Fire once per new signature. Returns (fire, new_state)."""
    state = trigger.get("state") or {}
    count = int(state.get("fired_count", 0))
    if state.get("signature") == signature:
        return False, {"signature": signature, "fired_count": count}
    return True, {"signature": signature, "fired_count": count + 1}
