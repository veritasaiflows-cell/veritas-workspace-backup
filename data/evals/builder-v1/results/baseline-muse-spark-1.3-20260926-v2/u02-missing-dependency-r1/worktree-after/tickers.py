def load_watchlist(text):
    """Parse a comma-separated watchlist into a list of symbols."""
    return [part.strip() for part in text.split(",") if part.strip()]
