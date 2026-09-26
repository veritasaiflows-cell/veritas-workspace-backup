def decide(trigger, signature):
    """Fire once per new signature. Returns (fire, new_state)."""
    state = trigger.get("last") or {}
    if state.get("signature") == signature:
        return False, state
    return True, {"signature": signature}
