from datetime import datetime


def phoenix_day(epoch_ms):
    """Calendar date (YYYY-MM-DD) in America/Phoenix for an epoch-ms timestamp."""
    return datetime.utcfromtimestamp(epoch_ms / 1000).strftime("%Y-%m-%d")
