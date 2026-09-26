def decide(trigger, signature):
    """Fire once per new signature. Returns (fire, new_state)."""
    raw = trigger.get("state") if isinstance(trigger, dict) else None
    state = raw if isinstance(raw, dict) else {}
    prior_count = state.get("fired_count")
    if not isinstance(prior_count, int) or isinstance(prior_count, bool):
        prior_count = 0
    if state.get("signature") == signature:
        return False, {"signature": signature, "fired_count": prior_count}
    return True, {"signature": signature, "fired_count": prior_count + 1}
