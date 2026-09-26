import time


def fetch_with_retry(fetch, attempts=3, sleep=None):
    """Call fetch() up to attempts times with exponential backoff on OSError."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if sleep is None:
        sleep = time.sleep
    delay = 1
    for attempt in range(attempts):
        try:
            return fetch()
        except OSError:
            if attempt == attempts - 1:
                raise
            sleep(delay)
            delay = min(delay * 2, 8)
