from datetime import datetime, timedelta, timezone

PHOENIX = timezone(timedelta(hours=-7))


def phoenix_day(epoch_ms):
    """Calendar date (YYYY-MM-DD) in America/Phoenix for an epoch-ms timestamp."""
    return datetime.fromtimestamp(epoch_ms / 1000, tz=PHOENIX).strftime("%Y-%m-%d")


def day_bounds_ms(day):
    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=PHOENIX)
    end = start + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)
